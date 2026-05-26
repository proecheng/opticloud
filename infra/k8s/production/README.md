# Production Kubernetes Network Domains

Story M3.3a defines the standard-tier production namespace boundary:

| Namespace | Domain label | Role |
|---|---|---|
| `prod-core` | `core` | API, orchestration, user-facing control plane |
| `prod-ai` | `ai` | AI / critic / sandbox-adjacent workloads |
| `prod-data` | `data` | Datastores and data-adjacent workloads |

The intended application-domain flow is one-way:

```text
prod-core -> prod-ai -> prod-data
prod-core -> prod-data
```

Reverse application-domain flows are denied by default-deny egress plus the absence of reverse allow policies:

- `prod-data -> prod-core`
- `prod-data -> prod-ai`
- `prod-ai -> prod-core`

Same-namespace traffic and DNS egress to `kube-system` / `k8s-app=kube-dns` are allowed in each domain.

## ACK Notes

NetworkPolicy enforcement depends on the cluster CNI implementing `networking.k8s.io/v1` NetworkPolicy. The standard-tier target is Alibaba Cloud ACK with a NetworkPolicy-capable CNI such as Terway. Do not treat static manifest validation as live enforcement proof.

## Local Validation

```powershell
uv run python scripts/validate_k8s_network_policies.py infra/k8s/production
uv run pytest tests/test_k8s_network_policies.py -q
```

## Real Cluster Validation

Run these only against a prepared ACK cluster with representative test pods/services:

```bash
kubectl apply --server-side --dry-run=server -f infra/k8s/production/
kubectl apply -f infra/k8s/production/
kubectl exec -n prod-data deploy/netcheck -- curl --max-time 5 http://service.prod-core
kubectl exec -n prod-core deploy/netcheck -- curl --max-time 5 http://service.prod-data
```

Expected result: `prod-data -> prod-core` fails or times out; `prod-core -> prod-data` succeeds once the destination service exists.

This story intentionally does not add Deployments, Services, Ingress, Service Mesh, mTLS, ArgoCD, ACK One GitOps, Helm, Terraform, or the M3.3b docker-compose blue-green path.
