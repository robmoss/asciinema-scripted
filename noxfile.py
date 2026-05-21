import nox


@nox.session()
def build(session):
    """Build source and binary (wheel) packages."""
    session.install('build')
    session.run('python', '-m', 'build')


@nox.session()
def ruff(session):
    """Check code for linter warnings and formatting issues."""
    check_files = ['src', 'tests', 'noxfile.py']
    session.install('ruff >= 0.15')
    session.run('ruff', 'check', *check_files)
    session.run('ruff', 'format', '--diff', *check_files)


@nox.session()
def mypy(session):
    """Check code for type errors."""
    session.install('.[tests,typing]', 'mypy')
    session.run('mypy', 'src', 'tests')


@nox.session()
def pyrefly(session):
    """Check code for type errors."""
    session.install('.[tests,typing]', 'pyrefly')
    session.run('pyrefly', 'check', 'src', 'tests')


@nox.session()
def tests(session):
    """Run test cases and record the test coverage."""
    session.install('.[yaml,tests]')
    # Run the test cases and report the test coverage.
    package = 'asciinema_scripted'
    session.run(
        'python3',
        '-m',
        'pytest',
        f'--cov={package}',
        '--pyargs',
        package,
        './tests',
        *session.posargs,
    )
    # Ensure that regression test outputs have not changed.
    session.run(
        'git', 'diff', '--exit-code', '--stat', 'tests/', external=True
    )
