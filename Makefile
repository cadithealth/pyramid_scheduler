PROJECT = pyramid_scheduler

test:
	nosetests --verbose

upload:
	python setup.py sdist upload

clean:
	find . -iname '*.pyc' -exec rm {} \;
	rm -fr "$(PROJECT).egg-info" dist

tag:
	@echo "[  ] tagging as version `cat VERSION.txt`..."
	git tag -a "v`cat VERSION.txt`" -m "released v`cat VERSION.txt`"

