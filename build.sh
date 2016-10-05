#!/usr/bin/env bash

VERSION='0.9.0a1'
TARBALL="txjuju_$VERSION.orig.tar.gz"
SOURCE_DIR="txjuju-$VERSION"
if [ -z $PROJECT_DIR ]; then
    PROJECT_DIR="$HOME/src/txjuju"
fi

echo '-- cleaning up --'
rm *.deb \
   *.debian.tar.xz \
   *.dsc \
   *.changes
rm -r $SOURCE_DIR

if [ -e txjuju-$VERSION.tar.gz ]; then
    echo '-- fixing tarball filename --'
    mv txjuju-$VERSION.tar.gz $TARBALL
fi

echo '-- unpacking --'
tar -xf $TARBALL
cp -r $PROJECT_DIR/debian $SOURCE_DIR

echo '-- building --'
pushd txjuju-$VERSION
dpkg-buildpackage -us -uc
