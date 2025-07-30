#!/bin/bash

echo "=== GitHub Push Helper Script ==="
echo ""

echo "Current branch:"
git branch --show-current

echo ""
echo "Remote repositories:"
git remote -v

echo ""
echo "Attempting to push to main branch..."
git push origin main

echo ""
echo "If the above failed due to authentication, try one of these methods:"
echo ""
echo "1. Use GitHub CLI (if installed):"
echo "   gh auth login"
echo "   git push origin main"
echo ""
echo "2. Use Personal Access Token:"
echo "   git remote set-url origin https://YOUR_TOKEN@github.com/SJLVamsi/Test.git"
echo "   git push origin main"
echo ""
echo "3. Use GitHub Desktop application for easier authentication"
echo ""
echo "4. Use SSH (if configured):"
echo "   git remote set-url origin git@github.com:SJLVamsi/Test.git"
echo "   git push origin main"
