# MacOS
# must be called with `source ~/git/paperwork/ci/from_brew_to_jhbuild.sh`

export PATH=$(echo $PATH | sed 's#^/usr/local/bin:##g' | sed 's#:/usr/local/bin$##g' | sed 's#:/usr/local/bin:##g')
echo Brew disabled

if [ -f ~/.new_local/env ]; then
	source ~/.new_local/env
	echo Jhbuild enabled
else
	echo "Cannot enable Jhbuild. ~/.new_local/env not found"
fi

