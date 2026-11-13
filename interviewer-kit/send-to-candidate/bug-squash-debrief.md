# Bug squash: debrief notes

Three bugs were planted in Mako 1.3.12. Five tests fail at the start, and all
of them pass once the three fixes below are in.

| Bug | Failing tests | Where the bug is |
| --- | --- | --- |
| 1 | `test_nested_loops` and `test_parent_loops` in `test/test_loop.py` | `LoopStack._exit` in `mako/runtime.py` |
| 2 | `test_convert_str` and `test_convert_str_before_custom_filter` in `test/test_filters.py` | `create_filter_callable` in `mako/codegen.py` |
| 3 | `test_alternating_file_names` in `test/test_exceptions.py` | `RichTraceback._init` in `mako/exceptions.py` |

One idea unlocks all three: Mako compiles a template into a Python module, and
`Template(...).code` shows you that module. The failing test is where the
problem was noticed, not where it lives.

## Bug 1: the loop stack returns the wrong context

**What you see.** `test_nested_loops` expects `a 0 <- back to outer loop` and
gets `a 2 <- back to outer loop`. The 2 belongs to the inner loop: it is that
loop's `index` after its two passes.

**A good path.**

1. Run only that test with short tracebacks:
   `python -m pytest test/test_loop.py -k nested --tb=short`.
2. Hypothesis: after the inner loop, the name `loop` still refers to the inner
   loop's context.
3. Look at what `loop` is. Print `template.code`, or read it in pytest's
   output: `test_parent_loops` prints it, under "Captured stdout call". The
   generated module does `loop = __M_loop._enter(...)` before each `for`, and
   `loop = __M_loop._exit()` in a `finally` after it.
4. Open `LoopStack` in `mako/runtime.py`; the assertion message names that
   class. `_enter` pushes a context and returns the top of the stack. `_exit`
   should pop and return the new top. It returns the context it just popped.

**Fix.**

```diff
--- a/mako/runtime.py
+++ b/mako/runtime.py
@@ -254,7 +254,8 @@
         return self._top
 
     def _exit(self):
-        return self._pop()
+        self._pop()
+        return self._top
 
     @property
     def _top(self):
```

**A fix that passes the tests but is not the same.**
`return self._pop().parent` turns both tests green. After the outermost loop
it leaves `loop` as `None`, so a later `${loop.index}` fails with an
`AttributeError` instead of Mako's own "No loop context is established".

## Bug 2: default filters are applied last instead of first

**What you see.** `test_convert_str` ends in
`AttributeError: 'int' object has no attribute 'strip'`. The traceback's last
frame is `filters.trim`, called from line 22 of an in-memory template module.
`test_convert_str_before_custom_filter` fails with `[5] != ['5']`.

**A good path.**

1. Read the test's docstring: string conversion must happen before the value
   reaches a filter.
2. Look at the generated code: `print(Template("${x | trim}").code)` shows
   `__M_writer(str(filters.trim(x )))`. The order is inside out.
3. Find where that expression is built. Searching for `default_filters` leads
   to `create_filter_callable` in `mako/codegen.py`.
4. Read the loop at the end of that function. Each filter wraps the target in
   turn, so the first name in `args` becomes the innermost call. The default
   filters therefore have to be at the front of the list, and the code puts
   them at the back.

**Fix.**

```diff
--- a/mako/codegen.py
+++ b/mako/codegen.py
@@ -790,7 +790,7 @@
                 if self.compiler.pagetag:
                     args = self.compiler.pagetag.filter_args.args + args
                 if self.compiler.default_filters and "n" not in args:
-                    args = args + self.compiler.default_filters
+                    args = self.compiler.default_filters + args
         for e in args:
             # if filter given as a function, get just the identifier portion
             if e == "n":
```

**Two tempting wrong fixes.** Changing `filters.trim` to call `str()` makes
`test_convert_str` pass. It treats the symptom: every other filter still gets
the raw value, which is what `test_convert_str_before_custom_filter` checks.
Reversing the loop instead (`for e in reversed(args)`) turns both tests green,
but the filters you write are then applied right to left:
`${x | first, second}` compiles to `first(second(str(x )))`.

## Bug 3: a stale variable in the traceback cache

**What you see.** Compare the expected text with the actual text line by line.
The line numbers and the source lines are right. Only the file name is wrong,
and only on the third and fourth frames, which say `foo.html` where
`base.html` is expected.

**A good path.**

1. Conclusion from the comparison: the line mapping works, so look at where the
   file name comes from.
2. Follow the call: `exceptions.text_error_template()` renders
   `RichTraceback().traceback`, and those records are built in
   `RichTraceback._init`.
3. Put a breakpoint inside the loop in `_init`, or print `filename` and
   `template_filename` on every pass. The compiled modules come in the order
   base, foo, base, base.
4. On passes three and four the `mods` cache is hit. The cache holds the line
   map and the template lines, but not the template's file name, so
   `template_filename` still holds whatever the previous pass left in it.

**Fix.**

```diff
--- a/mako/exceptions.py
+++ b/mako/exceptions.py
@@ -158,7 +158,7 @@
             if not line:
                 line = ""
             try:
-                (line_map, template_lines) = mods[filename]
+                (line_map, template_lines, template_filename) = mods[filename]
             except KeyError:
                 try:
                     info = mako.template._get_module_info(filename)
@@ -194,7 +194,7 @@
                 template_lines = [
                     line_ for line_ in template_source.split("\n")
                 ]
-                mods[filename] = (line_map, template_lines)
+                mods[filename] = (line_map, template_lines, template_filename)
 
             template_ln = line_map[lineno - 1]
 
```

**Worth noticing.** `template_source` is left over from the previous pass in
exactly the same way, and that is true of the original Mako code as well. No
test covers it. Spotting it shows that you understood the loop rather than
just the failing assertion.

## What a strong session looks like

- The whole suite is run first, then one failing test at a time.
- Every step starts with a prediction: "if I am right, this will print 2".
- Tools are used on purpose: a breakpoint in the loop, `template.code`, a
  search for a name, `git diff` before calling a fix done.
- Each fix comes with an explanation of the root cause, and the full suite is
  run again afterwards.
