from setuptools import find_namespace_packages, setup

if __name__ == "__main__":
    packages = find_namespace_packages(include=["_class*", "_core*", "_function*", "game_engine*", "i18n*", "multiplayer*", "_balance*"])
    setup(
        packages=["jeuxRPG", *[f"jeuxRPG.{name}" for name in packages]],
        package_dir={"jeuxRPG": "."},
        package_data={"jeuxRPG": ["_class/**/*.json", "i18n/translations/*.json", "multiplayer/web/*", "_balance/**/*.json"]},
    )
