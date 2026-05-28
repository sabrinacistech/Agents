#Requires -Version 5.1
<#
.SYNOPSIS
    Runs the Java test-coverage agent pipeline against a local Java project.

.DESCRIPTION
    Orchestrates all 16 pipeline steps:
      1-5   Scanning + extraction (POM, archetype, generated code, classpath, stack)
      6-8   Bytecode + source enrichment + optional JaCoCo
      9-11  Semantic index, classification, dependency graph
      12-14 Fixture catalog, coverage planner, optional incremental map
      15-16 State validation + context-pack builder (LLM input)

    Windows-safe: forces UTF-8, resolves mvn.cmd/mvn.bat, uses absolute paths.

.PARAMETER Repo
    Root of the Java module (must contain pom.xml + target/classes after build).
    Default: C:\repo\multi-clusters\cluster-status-service

.PARAMETER StateDir
    Directory where all state JSON files are written.
    Default: <AgentsRoot>\java-test-coverage-architecture\state

.PARAMETER Module
    Maven module name for bytecode scanning. Use '.' for monolithic repos (default).

.PARAMETER Build
    Run 'mvn.cmd -DskipTests package' before the pipeline.

.PARAMETER WithJaCoCo
    Run 'mvn.cmd test', then feed the resulting jacoco.xml to the pipeline (step 8).

.PARAMETER JaCoCoXml
    Path to a pre-existing jacoco.xml. Cannot be combined with -WithJaCoCo.

.PARAMETER Since
    Git ref for incremental analysis (e.g. HEAD~1, main). Enables step 14.

.PARAMETER Sut
    Restrict context-pack building (step 16) to a single FQCN.

.PARAMETER SkipSteps
    Space-separated list of step names to skip (pom archetype generated classpath
    stack bytecode source jacoco index classification deps fixtures planning
    incremental validate context).

.PARAMETER CoverageMode
    Scoring mode: coverage | branch-coverage | mutation-hardening (default: coverage).

.PARAMETER Compact
    DEPRECATED: compact context-packs are now produced by the pipeline by
    default (P1.a). Kept as a no-op for backwards compatibility.

.PARAMETER NoCompactPacks
    DEPRECATED (audit 2026-05-28): compact packs are now mandatory. Flag is
    accepted for backwards compatibility but only emits a warning; the
    pipeline always writes state/context-packs-compact/ and llm-budget.json.

.PARAMETER ContinueOnError
    Continue pipeline even if a step fails (legacy mode).

.EXAMPLE
    # Minimal run (project already built):
    .\run_agents.ps1

.EXAMPLE
    # Force Maven build + JaCoCo coverage:
    .\run_agents.ps1 -Build -WithJaCoCo

.EXAMPLE
    # Single SUT with pre-existing jacoco.xml:
    .\run_agents.ps1 -JaCoCoXml C:\repo\multi-clusters\cluster-status-service\target\site\jacoco\jacoco.xml -Sut com.company.service.ClusterStatusService

.EXAMPLE
    # Incremental run since last commit:
    .\run_agents.ps1 -Since HEAD~1
#>

[CmdletBinding()]
param(
    [string]$Repo      = "C:\repo\multi-clusters\cluster-status-service",
    [string]$StateDir = "",
    [string]$Module   = ".",
    [switch]$Build,
    [switch]$WithJaCoCo,
    [string]$JaCoCoXml = "",
    [string]$Since     = "",
    [string]$Sut       = "",
    [string]$SkipSteps = "",
    [ValidateSet("coverage","branch-coverage","mutation-hardening")]
    [string]$CoverageMode = "coverage",
    [switch]$Compact,
    [switch]$NoCompactPacks,
    [switch]$ContinueOnError
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── 0. UTF-8 console encoding ─────────────────────────────────────────────────
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8       = "1"

# ── 1. Resolve paths ──────────────────────────────────────────────────────────
$ScriptDir = $PSScriptRoot
$AgentsRoot = $ScriptDir
$ToolsDir = Join-Path $AgentsRoot "java-test-coverage-architecture\tools\python"
$PipelineScript = Join-Path $ToolsDir "run_pipeline.py"

if ($StateDir -eq "") {
    $StateDir = Join-Path $AgentsRoot "java-test-coverage-architecture\state"
}

$Repo = (Resolve-Path $Repo -ErrorAction Stop).ProviderPath

# ── 2. Banner ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Java Test-Coverage Agent Pipeline" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Agents root : $AgentsRoot"
Write-Host "  Target repo : $Repo"
Write-Host "  State dir   : $StateDir"
Write-Host "  Module      : $Module"
Write-Host "  Coverage    : $CoverageMode"
if ($Sut -ne "")   { Write-Host "  SUT filter  : $Sut" }
if ($Since -ne "") { Write-Host "  Incremental : since $Since" }
Write-Host ""

# ── 3. Validate prerequisites ─────────────────────────────────────────────────
Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Yellow

# --- Python (3.9+) ---
$Python = ""
$PythonCandidates = @("python", "python3", "py")
foreach ($candidate in $PythonCandidates) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { continue }
    $verOut = & $candidate --version 2>&1
    $verStr = "$verOut"
    if ($verStr -match "Python 3\.(\d+)") {
        $minorVer = [int]$Matches[1]
        if ($minorVer -lt 9) {
            Write-Warning "  $verStr found but 3.9+ required."
            continue
        }
        $Python = $candidate
        Write-Host "  [OK] $verStr (cmd: $candidate)"
        break
    }
}
if ($Python -eq "") {
    Write-Error "Python 3.9+ not found. Install from https://python.org and add to PATH."
}

# --- Java / javap ---
$JavapCmd = Get-Command javap -ErrorAction SilentlyContinue
if ($null -ne $JavapCmd) {
    Write-Host "  [OK] javap: $($JavapCmd.Source)"
} else {
    Write-Warning "  [WARN] javap not found -- bytecode scanning (step 6) will fail."
    Write-Warning "         Add JAVA_HOME\bin to PATH."
}

# --- Maven ---
$MvnCmd = ""
$MvnCandidates = @("mvn.cmd", "mvn.bat", "mvn")
foreach ($candidate in $MvnCandidates) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($null -ne $cmd) {
        $MvnCmd = $cmd.Source
        Write-Host "  [OK] Maven: $MvnCmd"
        break
    }
}
if ($MvnCmd -eq "") {
    if ($Build -or $WithJaCoCo) {
        Write-Error "Maven not found on PATH but -Build / -WithJaCoCo requires it. Install Maven 3.9+."
    } else {
        Write-Host "  [--] Maven not on PATH (OK -- not building)"
    }
}

# --- pom.xml ---
$PomPath = Join-Path $Repo "pom.xml"
if (-not (Test-Path $PomPath)) {
    Write-Error "No pom.xml found at: $Repo -- check the -Repo parameter."
}

# ── 4. Python virtual environment ─────────────────────────────────────────────
Write-Host ""
Write-Host "[2/6] Setting up Python virtual environment..." -ForegroundColor Yellow

$VenvDir = Join-Path $AgentsRoot ".venv"
$VenvPy  = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $VenvPy)) {
    Write-Host "  Creating venv at $VenvDir ..."
    & $Python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Python virtual environment."
    }
}

Write-Host "  Upgrading pip and installing requirements..."
& $VenvPip install --quiet --upgrade pip
$RequirementsFile = Join-Path $ToolsDir "requirements.txt"
& $VenvPip install --quiet -r $RequirementsFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install failed -- check $RequirementsFile"
}
Write-Host "  [OK] venv ready: $VenvDir"
$PythonExe = $VenvPy

# ── 5. Optional Maven build ───────────────────────────────────────────────────
Write-Host ""
if ($Build) {
    Write-Host "[3/6] Building Java project (mvn -DskipTests package)..." -ForegroundColor Yellow
    Push-Location $Repo
    & $MvnCmd -DskipTests package --batch-mode
    $MvnExit = $LASTEXITCODE
    Pop-Location
    if ($MvnExit -ne 0) {
        Write-Error "Maven build failed (exit $MvnExit)."
    }
    Write-Host "  [OK] Build complete"
} else {
    $ClassesDir = Join-Path $Repo "target\classes"
    if (Test-Path $ClassesDir) {
        Write-Host "[3/6] Maven build skipped (target\classes already exists)" -ForegroundColor DarkGray
    } else {
        Write-Host "[3/6] Maven build skipped -- target\classes NOT FOUND!" -ForegroundColor Red
        Write-Host "      Run with -Build flag or: mvn.cmd -DskipTests package"
        Write-Host "      Bytecode scanning (step 6) will fail without compiled classes."
    }
}

# ── 5b. Optional JaCoCo test run ──────────────────────────────────────────────
$JaCoCoPath = ""
if ($WithJaCoCo -and ($JaCoCoXml -ne "")) {
    Write-Error "-WithJaCoCo and -JaCoCoXml cannot be used together. Choose one."
}

if ($WithJaCoCo) {
    Write-Host ""
    Write-Host "[3b] Running tests + JaCoCo (mvn test)..." -ForegroundColor Yellow
    Push-Location $Repo
    & $MvnCmd test --batch-mode
    $MvnTestExit = $LASTEXITCODE
    Pop-Location
    if ($MvnTestExit -ne 0) {
        Write-Warning "  [WARN] Tests finished with exit $MvnTestExit. JaCoCo XML may be partial."
    }
    $JaCoCoSearchPaths = @(
        (Join-Path $Repo "target\site\jacoco\jacoco.xml"),
        (Join-Path $Repo "target\jacoco.xml"),
        (Join-Path $Repo "target\jacoco-ut\jacoco.xml")
    )
    foreach ($p in $JaCoCoSearchPaths) {
        if (Test-Path $p) {
            $JaCoCoPath = $p
            break
        }
    }
    if ($JaCoCoPath -eq "") {
        Write-Warning "  [WARN] jacoco.xml not found after test run. Step 8 will be skipped."
    } else {
        Write-Host "  [OK] JaCoCo report: $JaCoCoPath"
    }
}

if ($JaCoCoXml -ne "") {
    if (-not (Test-Path $JaCoCoXml)) {
        Write-Error "JaCoCo XML not found: $JaCoCoXml"
    }
    $JaCoCoPath = (Resolve-Path $JaCoCoXml).ProviderPath
    Write-Host "  [OK] Using existing JaCoCo: $JaCoCoPath"
}

# ── 6. Build pipeline arguments ───────────────────────────────────────────────
Write-Host ""
Write-Host "[4/6] Composing pipeline arguments..." -ForegroundColor Yellow

$StateDirNorm = $StateDir -replace '\\', '/'
New-Item -ItemType Directory -Path $StateDir -Force | Out-Null

$PipelineArgs = @(
    $PipelineScript,
    "--repo", $Repo,
    "--out",  $StateDirNorm,
    "--module", $Module,
    "--coverage-mode", $CoverageMode
)

if ($JaCoCoPath -ne "") {
    $PipelineArgs += @("--jacoco-xml", $JaCoCoPath)
}

if ($Since -ne "") {
    $PipelineArgs += @("--since", $Since)
}

if ($Sut -ne "") {
    $PipelineArgs += @("--sut", $Sut)
}

if ($SkipSteps -ne "") {
    $steps = $SkipSteps -split '\s+' | Where-Object { $_ -ne "" }
    $PipelineArgs += @("--skip") + $steps
}

if ($ContinueOnError) {
    $PipelineArgs += @("--continue-on-error")
}

if ($NoCompactPacks) {
    Write-Host "  [WARN] -NoCompactPacks is deprecated; compact packs are mandatory. Flag ignored." -ForegroundColor DarkYellow
}

if ($Compact) {
    Write-Host "  [INFO] -Compact is deprecated; compact packs are produced by default." -ForegroundColor DarkYellow
}

Write-Host "  $PythonExe $($PipelineArgs -join ' ')"

# ── 7. Run the pipeline ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/6] Running pipeline (16 steps)..." -ForegroundColor Yellow
Write-Host "      Output is streamed live. Each step prints [OK] or [FAIL]."
Write-Host ""

$t0 = Get-Date

& $PythonExe @PipelineArgs
$PipelineExit = $LASTEXITCODE

$elapsedSec = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)

# ── 8. (Removed) Compact pass is now part of the pipeline by default ─────────
# P1.b: the previous opt-in second pass over context_pack_builder.py was
# redundant — run_pipeline.py Step 16 now emits compact packs and the
# per-SUT llm-budget.json by default.

# ── 9. Results summary ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
if ($PipelineExit -eq 0) {
    Write-Host ("  PIPELINE COMPLETE  ({0}s)" -f $elapsedSec) -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  State files written to:"
    Write-Host "    $StateDir" -ForegroundColor White
    Write-Host ""

    $PacksDir = Join-Path $StateDir "context-packs"
    if (Test-Path $PacksDir) {
        $packs = Get-ChildItem $PacksDir -Filter "*.json" -ErrorAction SilentlyContinue
        $packCount = ($packs | Measure-Object).Count
        Write-Host "  Context packs ready for LLM agents: $packCount" -ForegroundColor Green
        $packs | Select-Object -First 10 | ForEach-Object {
            Write-Host "    - $($_.Name)"
        }
        if ($packCount -gt 10) {
            Write-Host "    ... and $($packCount - 10) more"
        }
    }

    $FailurePath = Join-Path $StateDir "_summaries\last-failure.json"
    if (Test-Path $FailurePath) {
        Write-Host ""
        Write-Host "  Note: last-failure.json present (non-fatal step errors logged there)" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "  Next step: feed context-packs to the LLM coverage agent." -ForegroundColor Cyan
    Write-Host "  Reference: MASTER_PROMPT.md / BOOT.md in java-test-coverage-architecture\"
} else {
    Write-Host ("  PIPELINE FAILED  (exit {0}, {1}s)" -f $PipelineExit, $elapsedSec) -ForegroundColor Red
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host ""
    $FailurePath = Join-Path $StateDir "_summaries\last-failure.json"
    if (Test-Path $FailurePath) {
        Write-Host "  Failure details:" -ForegroundColor Red
        Get-Content $FailurePath | Write-Host
    } else {
        Write-Host "  Check the [FAIL] lines in the output above." -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "  Common fixes:"
    Write-Host "    - No target\classes  --> run with -Build flag"
    Write-Host "    - javap not found    --> add JAVA_HOME\bin to PATH"
    Write-Host "    - Schema validation  --> check state\_summaries\last-failure.json"
}
Write-Host ""

exit $PipelineExit
