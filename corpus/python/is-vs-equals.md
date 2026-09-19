# `is` versus `==`

`==` asks whether two objects have equal values. `is` asks whether they are the
very same object in memory. Two separate lists holding the same items are
equal, but they are not identical.

```python
a = [1, 2]
b = [1, 2]
a == b   # True
a is b   # False
```

Use `==` to compare values. Use `is` only for singletons, and in this course
that means `is None` and `is not None`. Small integers and short strings may
appear to work with `is` because Python reuses them, but that is an
implementation detail and we do not rely on it.
