from pathlib import Path

path = Path("buggy_math.py")
text = path.read_text(encoding="utf-8")
text = text.replace("return a - b", "return a / b")
path.write_text(text, encoding="utf-8")
print("patched divide implementation")
