from pathlib import Path

Path("hello.py").write_text('print("changed by traceforge command")\n', encoding="utf-8")
print("hello.py modified")
