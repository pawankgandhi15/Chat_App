def pytest_addoption(parser):
    parser.addoption("--integration", action="store_true", help="Run isolated real Docker/Redis tests")
    parser.addoption("--browser-url", default=None, help="Run browser tests against this gateway URL")
