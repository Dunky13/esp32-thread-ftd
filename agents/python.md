# Python Agent Rules

Use for repo-local Python tooling such as:

- `tools/*.py`
- `tools/tests/*.py`

Validation:

- Run focused repo-local tests first:

```bash
python3 -m unittest tools.tests.test_robustness
```

- If only one behavior changed, prefer running or updating targeted test cases over broader firmware workflows.
- Use full provisioning or build flows only when Python change affects command wiring, generated outputs, or flashing behavior end to end.

Factory-data and onboarding notes:

- `tools/generate_factory_data.py` shells into Matter generator `generate_esp32_chip_factory_bin.py`.
- That generator depends on extra CHIP Python packages beyond `esp-matter/requirements.txt`.
- For setup-payload generation, dependency source of truth is:

```text
esp-matter/connectedhomeip/connectedhomeip/scripts/setup/requirements.setuppayload.txt
```

- Missing `python_stdnum` or `stdnum` errors usually mean that requirements file was not installed into active IDF/tool Python env.
- Report missing env deps clearly. Do not pretend repo logic is broken if failure is pure env setup.
