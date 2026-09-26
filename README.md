# TraceProof

[![TraceProof CI](https://github.com/YOUR_ORG/traceproof/actions/workflows/traceproof.yml/badge.svg)](https://github.com/YOUR_ORG/traceproof/actions/workflows/traceproof.yml)

Requirements traceability audit toolkit — extract, index, run tests, and build an RTM from a spec document.

## Quick start

```bash
pip install -e .
traceproof scan   --spec demo/specs/PayFlow_SRS_v1.2.pdf --repo demo/payflow
traceproof report --repo demo/payflow --spec demo/specs/PayFlow_SRS_v1.2.pdf
traceproof check  --repo demo/payflow --min-coverage 100
```
