
# To get a basic debian directory:
sudo apt-get install python-stdeb
python2 setup.py --command-packages=stdeb.command sdist_dsc
cp -r deb_dist/txjuju-0.9.0a1/debian .

# To build a basic installable binary package:
python2 setup.py --command-packages=stdeb.command bdist_deb

# To build complete from scratch:
mkdir -p /tmp/txjuju/txjuju-0.9.0a1
cp -r debian /tmp/txjuju/txjuju-0.9.0a1
python2 setup.py sdist --dist-dir /tmp/txjuju
pushd /tmp/txjuju
tar -xf txjuju-0.9.0a1.tar.gz
mv txjuju-0.9.0a1.tar.gz txjuju_0.9.0a1.orig.tar.gz
cd txjuju-0.9.0a1
dpkg-buildpackage -us -uc
