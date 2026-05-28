# Installing TraceForge

TraceForge is published to PyPI as `traceforge-ai`. The installed command is still `traceforge`.

## Requirements

- Python 3.10+
- Git
- A Git project if you want meaningful diff capture

## Install from PyPI

```bash
python -m pip install traceforge-ai
traceforge version
```

## Local development install

```bash
git clone https://github.com/zhangyeS12/traceforge.git
cd traceforge
python -m pip install -e .
traceforge version
```

## Verify the installation

```bash
traceforge doctor
traceforge selftest
```

## Windows notes

PowerShell can treat `<` and `>` as special redirection characters. When documentation says:

```text
traceforge timeline <run_id>
```

replace `<run_id>` with the actual ID and do not type the angle brackets:

```powershell
traceforge timeline 20260527-201546-eb50faf7
```

For shell features such as `&&`, pipes, and redirects, use:

```powershell
traceforge run --shell -- "python a.py && python b.py"
```
