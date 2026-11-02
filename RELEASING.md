# Releasing to PyPI

Replace `X.Y.Z` with the new version in all commands below.

1. Set `version` in `pyproject.toml` to `X.Y.Z`. The docs read the version from this file.

2. Merge all changes into `master`, then build from there:

   ```bash
   git switch master
   git pull
   pip install build twine
   python -m build
   ```

3. Check and upload the new version:

   ```bash
   twine check dist/camrcs-X.Y.Z*
   twine upload dist/camrcs-X.Y.Z*
   ```

   Use `__token__` as the username and a PyPI API token as the password.

   - Name the version explicitly: `dist/` also holds older builds, which `dist/*` would try to upload.
   - PyPI does not allow a version to be replaced after upload, so check everything first.

4. Tag the release and create it on GitHub:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   gh release create vX.Y.Z --generate-notes
   ```

5. Check that the [`stable` docs](https://camrcs.readthedocs.io/en/stable/) on Read the Docs show the new version.
