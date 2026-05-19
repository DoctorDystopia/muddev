# MUD DEVELOPMENT

When you eventually want to update Evennia to a newer version, you simply step into the submodule, pull the changes, and then commit the new hash at the top level:

cd evennia
git checkout master
git pull
cd ..
git add evennia
git commit -m "build: bump evennia submodule hash"
