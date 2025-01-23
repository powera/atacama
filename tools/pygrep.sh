find src -name "*.py" -type f -print0 | sort -z | xargs -0 grep "$1"
