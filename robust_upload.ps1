$env:HF_TOKEN="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"
$maxRetries = 15
$retryCount = 0
$success = $false

while (-not $success -and $retryCount -lt $maxRetries) {
    Write-Host "Starting upload attempt ($($retryCount + 1) of $maxRetries)..."
    hf upload bruhpika/cheme-phi3-GGUF E:\hobbies\ChemEng_finetuning-main\finetune . --repo-type model --include "*.gguf" --include "README.md"
    if ($LASTEXITCODE -eq 0) {
        $success = $true
        Write-Host "Upload completed successfully!"
    } else {
        $retryCount++
        Write-Host "Upload failed with exit code $LASTEXITCODE. Retrying in 15 seconds..."
        Start-Sleep -Seconds 15
    }
}

if (-not $success) {
    Write-Host "Failed after $maxRetries attempts."
}
