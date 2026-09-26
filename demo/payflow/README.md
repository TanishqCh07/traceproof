# PayFlow (sample target for TraceProof)

A small, dependency-free Python payments service used as the **audit target** in the TraceProof demo.
It is checked against `specs/PayFlow_SRS_v1.2.pdf`.

```bash
pip install pytest
python -m pytest -q
```

> Sample data only. It contains no real card data or personal information. `4111111111111111` is the industry-standard test PAN.
