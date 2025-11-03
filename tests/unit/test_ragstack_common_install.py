"""Unit tests for ragstack_common pip install approach"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSetupPy:
    """Tests for lib/setup.py structure and validity"""

    def test_setup_py_exists(self):
        """Verify lib/setup.py exists"""
        setup_path = Path("lib/setup.py")
        assert setup_path.exists(), "lib/setup.py should exist for package installation"

    def test_setup_py_valid_syntax(self):
        """Verify setup.py has valid Python syntax"""
        setup_path = Path("lib/setup.py")

        # Read and compile the setup.py file
        with open(setup_path) as f:
            setup_code = f.read()

        try:
            compile(setup_code, str(setup_path), "exec")
        except SyntaxError as e:
            pytest.fail(f"setup.py has invalid syntax: {e}")

    def test_setup_py_defines_ragstack_common_package(self):
        """Verify setup.py defines ragstack_common as the package name"""
        setup_path = Path("lib/setup.py")

        with open(setup_path) as f:
            content = f.read()

        assert 'name="ragstack_common"' in content, (
            "setup.py should define package name as 'ragstack_common'"
        )

    def test_setup_py_specifies_packages(self):
        """Verify setup.py specifies the ragstack_common package"""
        setup_path = Path("lib/setup.py")

        with open(setup_path) as f:
            content = f.read()

        assert "packages=" in content, "setup.py should specify packages"
        assert "ragstack_common" in content, (
            "setup.py should include ragstack_common in packages list"
        )

    def test_setup_py_has_required_dependencies(self):
        """Verify setup.py declares required dependencies"""
        setup_path = Path("lib/setup.py")

        with open(setup_path) as f:
            content = f.read()

        # Check for install_requires section
        assert "install_requires=" in content, "setup.py should have install_requires section"

        # Check for key dependencies
        assert "boto3" in content, "setup.py should include boto3 dependency"
        assert "PyMuPDF" in content, "setup.py should include PyMuPDF dependency"
        assert "Pillow" in content, "setup.py should include Pillow dependency"


class TestRagstackCommonStructure:
    """Tests for ragstack_common package structure"""

    def test_ragstack_common_directory_exists(self):
        """Verify lib/ragstack_common directory exists"""
        pkg_dir = Path("lib/ragstack_common")
        assert pkg_dir.exists(), "lib/ragstack_common directory should exist"
        assert pkg_dir.is_dir(), "lib/ragstack_common should be a directory"

    def test_ragstack_common_has_init(self):
        """Verify ragstack_common has __init__.py"""
        init_file = Path("lib/ragstack_common/__init__.py")
        assert init_file.exists(), "lib/ragstack_common/__init__.py should exist for Python package"

    def test_ragstack_common_has_required_modules(self):
        """Verify ragstack_common has all required modules"""
        required_modules = [
            "bedrock.py",
            "ocr.py",
            "storage.py",
            "models.py",
            "image.py",
        ]

        pkg_dir = Path("lib/ragstack_common")

        for module in required_modules:
            module_path = pkg_dir / module
            assert module_path.exists(), f"Required module {module} should exist in ragstack_common"


class TestLambdaRequirements:
    """Tests for Lambda functions requirements.txt"""

    def test_process_document_requirements_reference_lib(self):
        """Verify process_document requirements.txt references ./lib"""
        req_file = Path("src/lambda/process_document/requirements.txt")
        assert req_file.exists(), "process_document should have requirements.txt"

        content = req_file.read_text()
        assert "./lib" in content, "process_document requirements should reference ./lib package"

    def test_query_kb_does_not_reference_lib(self):
        """Verify query_kb doesn't reference lib (doesn't use ragstack_common)"""
        req_file = Path("src/lambda/query_kb/requirements.txt")

        if req_file.exists():
            content = req_file.read_text()
            assert "./lib" not in content and "ragstack_common" not in content, (
                "query_kb should not reference ragstack_common (doesn't import it)"
            )

    def test_lambda_functions_import_ragstack_common(self):
        """Verify Lambda functions that reference ./lib actually import ragstack_common"""
        functions_with_lib = [
            "process_document",
        ]

        for func_name in functions_with_lib:
            index_path = Path(f"src/lambda/{func_name}/index.py")
            assert index_path.exists(), f"{func_name}/index.py should exist"

            content = index_path.read_text()
            assert "from ragstack_common" in content or "import ragstack_common" in content, (
                f"{func_name} should import from ragstack_common"
            )


class TestPackageInstallation:
    """Tests for package installation mechanism"""

    def test_no_symlinks_in_lambda_directories(self):
        """Verify no symlinks exist in Lambda function directories"""
        lambda_dir = Path("src/lambda")

        # Check that shared/ symlink directory is gone
        shared_dir = lambda_dir / "shared"
        assert not shared_dir.exists(), "src/lambda/shared symlink directory should be removed"

        # Check no ragstack_common symlinks in Lambda function directories
        for func_dir in lambda_dir.iterdir():
            if func_dir.is_dir():
                ragstack_link = func_dir / "ragstack_common"
                if ragstack_link.exists():
                    assert not ragstack_link.is_symlink(), (
                        f"ragstack_common in {func_dir.name} should not be a symlink"
                    )

    def test_gitignore_excludes_build_artifacts(self):
        """Verify .gitignore excludes package build artifacts"""
        gitignore = Path(".gitignore")
        assert gitignore.exists(), ".gitignore should exist"

        content = gitignore.read_text()

        # Check for important exclusions
        assert "*.egg-info" in content or "*.egg-info/" in content, (
            ".gitignore should exclude .egg-info directories"
        )
        assert "build/" in content, ".gitignore should exclude build/ directory"
        assert ".aws-sam/" in content, ".gitignore should exclude .aws-sam/ directory"
        assert "layers/" in content, ".gitignore should exclude layers/ directory"


class TestNoObsoleteCode:
    """Tests to ensure obsolete layer-based code is removed"""

    def test_no_build_lambda_layers_function(self):
        """Verify build_lambda_layers() function has been removed"""
        publish_path = Path("publish.py")

        with open(publish_path) as f:
            content = f.read()

        assert "def build_lambda_layers" not in content, (
            "build_lambda_layers() function should be removed (obsolete)"
        )

    def test_sam_build_has_no_skip_layers_parameter(self):
        """Verify sam_build() no longer has skip_layers parameter"""
        publish_path = Path("publish.py")

        with open(publish_path) as f:
            content = f.read()

        # Check function signature
        assert "def sam_build(skip_layers" not in content, (
            "sam_build() should not have skip_layers parameter"
        )

        # Check no references to skip_layers anywhere
        assert "skip_layers" not in content, (
            "No references to skip_layers should exist in publish.py"
        )
