
# To get a basic debian directory:
sudo apt-get install python-stdeb
python2 setup.py --command-packages=stdeb.command sdist_dsc
cp -r deb_dist/txjuju-0.9.0a1/debian .

# To update the PPA:
cp deb_dist/txjuju_0.9.0a1.orig.tar.gz 
bzr bd -S
dput ppa:fginther/ci-ppa-1 txjuju_0.9.0a1-1~ppa1_source.changes
