# Terminal demo for the README. Regenerate with:  make gif
# Records the real CLI on the planted suite. The hunt takes about a minute and a half;
# the recording skips the wait between the progress lines and the report.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1240
Set Height 1060
Set Padding 16
Set Theme "GitHub Dark"
Set TypingSpeed 30ms

Hide
Type "export PS1='$ ' && cd /vhs/examples/planted && clear"
Enter
Show

Type "pytest -q 2>&1 | tail -1"
Enter
Sleep 3s
Type "flaky-hunt run --factors order,random,timing,network"
Enter
Sleep 4s
Hide
Sleep 120s
Show
Sleep 9s
Type "pytest -q --fh-switch-interval=1e-6 tests/test_inventory.py | tail -2"
Enter
Sleep 5s
