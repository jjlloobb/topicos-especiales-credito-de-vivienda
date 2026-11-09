# registry-verify: los CronJobs de verificacion (incluido registry-verify-ondemand) solo leen la llave publica (P-U3-08).
# NO firman: la firma es solo de registry-checkpoint y registry-archive.
path "transit/keys/registry-checkpoints" {
  capabilities = ["read"]
}
