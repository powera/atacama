# Check if pre-commit hook already exists
if [ -f .git/hooks/pre-commit ]; then
    echo "Error: pre-commit hook already exists"
    exit 1
fi

# Create the pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
python PRESUBMIT.py
if [ $? -ne 0 ]; then
    exit 1
fi
EOF

# Make it executable
chmod +x .git/hooks/pre-commit
