Write-Host "=== 1. CHECKING PYTHON UPLOAD PROCESSES ==="
$procs = Get-Process python -ErrorAction SilentlyContinue
if ($procs) {
    foreach ($p in $procs) {
        Write-Host "PID:" $p.Id "| CPU(s):" $p.CPU "| RAM(MB):" [math]::Round($p.WorkingSet64 / 1MB, 2)
        Write-Host "Active HTTPS Connections (Port 443) owned by PID $($p.Id):"
        $conns = Get-NetTCPConnection -OwningProcess $p.Id -State Established -ErrorAction SilentlyContinue | Where-Object { $_.RemotePort -eq 443 }
        if ($conns) {
            $conns | Select-Object LocalAddress, RemoteAddress, RemotePort, State | Format-Table -AutoSize
            Write-Host "Status: ACTIVE NETWORK STREAMING DETECTED! ($($conns.Count) parallel sockets open)" -ForegroundColor Green
        } else {
            Write-Host "Status: NO ACTIVE 443 SOCKETS OPEN FOR THIS PROCESS." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "No python.exe processes found running." -ForegroundColor Red
}

Write-Host "`n=== 2. MEASURING NETWORK TRANSMIT THROUGHPUT FOR 3 SECONDS ==="
try {
    $counters = Get-Counter "\Network Interface(*)\Bytes Sent/sec" -SampleInterval 3 -MaxSamples 1 -ErrorAction SilentlyContinue
    foreach ($c in $counters.CounterSamples) {
        $mbPerSec = [math]::Round($c.CookedValue / 1MB, 2)
        if ($mbPerSec -gt 0.05) {
            Write-Host "Interface '$($c.InstanceName)': Upload Rate = $mbPerSec MB/s ($([math]::Round($mbPerSec * 8, 2)) Mbps)" -ForegroundColor Cyan
        }
    }
} catch {
    Write-Host "Could not sample network counters: $_"
}

Write-Host "`n=== 3. CHECKING CACHE LOG & TASK STATUS ==="
$taskLog = "C:\Users\khars\.gemini\antigravity-cli\brain\8e493ebb-ad90-4b0b-a956-996dc1ed6f03\.system_generated\tasks\task-129.log"
if (Test-Path $taskLog) {
    Write-Host "Last 5 lines of task-129 output log:"
    Get-Content $taskLog -Tail 5
}
