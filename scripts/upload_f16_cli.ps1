$env:HF_TOKEN="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"
$maxRetries = 1000
$retryCount = 0
$success = $false

Write-Host "=== Starting Direct CLI LFS Upload for cheme-phi3-f16.gguf (7.12 GB) ==="
Write-Host "Using official hf upload engine (Proven to have uploaded Q4, Q5, and Q8 - 12.8 GB total!)"

while (-not $success -and $retryCount -lt $maxRetries) {
    $retryCount++
    Write-Host "`n=======================================================" -ForegroundColor Cyan
    Write-Host "--- CLI Attempt $retryCount of $maxRetries ($(Get-Date -Format 'HH:mm:ss')) ---" -ForegroundColor Cyan
    Write-Host "=======================================================" -ForegroundColor Cyan
    
    & "E:\hobbies\ChemEng_finetuning-main\.venv\Scripts\hf.exe" upload bruhpika/cheme-phi3-GGUF E:\hobbies\ChemEng_finetuning-main\finetune\cheme-phi3-f16.gguf cheme-phi3-f16.gguf --repo-type model --commit-message "Add cheme-phi3-f16.gguf (F16 Quantization)"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n[SUCCESS] cheme-phi3-f16.gguf SUCCESSFULLY UPLOADED AND COMMITTED!" -ForegroundColor Green
        $success = $true
    } else {
        Write-Host "`n[Notice] CLI interrupted (Exit code $LASTEXITCODE). Resuming exact block offset in 10 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
}
