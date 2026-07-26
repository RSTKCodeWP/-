#!/bin/bash
function clean {
	local targetDir=$1
	rm -rf "$targetDir/TestResults"
}


dotnet test --collect:"XPlat Code Coverage" --results-directory:"./.coverage"
dotnet tool install -g dotnet-reportgenerator-globaltool
reportgenerator "-reports:.coverage/**/*.cobertura.xml" "-targetdir:.coverage-report/" "-reporttypes:HTML;"

clean "OpenIPC_Config.Tests"
