# Fault Tolerance

The CLI writes a local PENDING journal entry before each write request, optionally asks the server for a checkpoint, sends the signed request, stores the server outcome, and updates the circuit breaker state. Checkpoints are stored on the server and, when enabled, mirrored locally under `~/.wrs/sites/<site>/checkpoints/`.

