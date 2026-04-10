#!/bin/bash
# Uso: bash commit.sh "ruta/archivo" "mensaje del commit"
git add -f "$1"
git commit -m "$2"
git push origin main
