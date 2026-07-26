#!/bin/bash

echo "Cleaning previous builds..."
rm -rf build

dotnet clean
find . -name bin -exec rm -rf {} +  
find . -name obj -exec rm -rf {} +  

echo "Done."