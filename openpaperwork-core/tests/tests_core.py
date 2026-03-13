import abc
import unittest
import unittest.mock

import openpaperwork_core


class TestLoading(unittest.TestCase):
    @unittest.mock.patch("importlib.import_module")
    def test_simple_loading(self, import_module):
        class TestInterface(abc.ABC):
            @abc.abstractmethod
            def test_method(self):
                ...

        class TestModule:
            __name__ = "whatever_module"

            class Plugin(openpaperwork_core.PluginBase, TestInterface):
                def __init__(self, core):
                    super().__init__(core)
                    self.init_called = True
                    self.test_method_called = False

                def test_method(self):
                    self.test_method_called = True

        core = openpaperwork_core.Core(auto_load_dependencies=True)

        import_module.return_value = TestModule()
        core.load('whatever_module')
        import_module.assert_called_once_with('whatever_module')

        core.init()
        self.assertTrue(core.get_by_name('whatever_module').init_called)

        core.call_all(TestInterface.test_method)
        self.assertTrue(core.get_by_name('whatever_module').test_method_called)


class TestInit(unittest.TestCase):
    @unittest.mock.patch("importlib.import_module")
    def test_init_order(self, import_module):
        global g_idx
        g_idx = 0

        class InterfaceA(abc.ABC):
            pass

        class InterfaceB(abc.ABC):
            pass

        class InterfaceC(abc.ABC):
            pass

        class TestModuleA:
            __name__ = "module_a"

            class Plugin(openpaperwork_core.PluginBase, InterfaceA):
                def __init__(self, core):
                    super().__init__(core)
                    global g_idx
                    self.init_called_a = True
                    g_idx += 1

        class TestModuleB:
            __name__ = "module_b"

            class Plugin(openpaperwork_core.PluginBase, InterfaceB):
                @classmethod
                def get_deps(cls):
                    return [
                        openpaperwork_core.Dependency(
                            interface=InterfaceA,
                            defaults=['module_a'],
                        )
                    ]

                def __init__(self, core):
                    super().__init__(core)
                    global g_idx
                    self.init_called_b = True
                    g_idx += 1

        class TestModuleC:
            __name__ = "module_c"

            class Plugin(openpaperwork_core.PluginBase, InterfaceC):
                @classmethod
                def get_deps(cls):
                    return [
                        openpaperwork_core.Dependency(
                            interface=InterfaceB,
                            defaults=['module_b'],
                        )
                    ]

                def __init__(self, core):
                    super().__init__(core)
                    global g_idx
                    self.init_called_c = True
                    g_idx += 1

        core = openpaperwork_core.Core(auto_load_dependencies=True)

        import_module.return_value = TestModuleA()
        core.load('module_a')
        import_module.assert_called_once_with('module_a')

        import_module.reset_mock()
        import_module.return_value = TestModuleC()
        core.load('module_c')
        import_module.assert_called_once_with('module_c')

        import_module.reset_mock()
        import_module.return_value = TestModuleB()
        core.init()  # will load 'module_b' because of dependencies
        import_module.assert_called_once_with('module_b')

        self.assertEqual(core.get_by_name('module_a').init_called_a, True)
        self.assertEqual(core.get_by_name('module_b').init_called_b, True)
        self.assertEqual(core.get_by_name('module_c').init_called_c, True)
        self.assertEqual(g_idx, 3)


class TestCall(unittest.TestCase):
    @unittest.mock.patch("importlib.import_module")
    def test_default_interface(self, import_module):
        class TestInterfaceB(abc.ABC):
            @abc.abstractmethod
            def test_method(self):
                ...

        class TestInterfaceC(abc.ABC):
            @abc.abstractmethod
            def test_method(self):
                ...

        class TestModuleB:
            __name__ = "module_b"

            class Plugin(openpaperwork_core.PluginBase, TestInterfaceB):
                def __init__(self, core):
                    super().__init__(core)
                    self.init_called_b = True
                    self.test_method_called_b = False

                def test_method(self):
                    self.test_method_called_b = True

        class TestModuleC:
            __name__ = "module_c"

            class Plugin(openpaperwork_core.PluginBase, TestInterfaceC):
                @classmethod
                def get_deps(cls):
                    return [
                        openpaperwork_core.Dependency(
                            interface=TestInterfaceB,
                            defaults=['module_a', 'module_b']
                        ),
                    ]

                def __init__(self, core):
                    super().__init__(core)
                    self.init_called_c = True
                    self.test_method_called_c = False

                def test_method(self):
                    self.test_method_called_c = True

        core = openpaperwork_core.Core(auto_load_dependencies=True)

        import_module.return_value = TestModuleC()
        core.load('module_c')
        import_module.assert_called_once_with('module_c')

        import_module.reset_mock()
        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        # interface already satisfied --> won't load 'module_a'
        core.init()

        self.assertTrue(core.get_by_name('module_b').init_called_b)
        self.assertTrue(core.get_by_name('module_c').init_called_c)

        core.call_all(TestInterfaceB.test_method)
        core.call_all(TestInterfaceC.test_method)
        self.assertTrue(core.get_by_name('module_b').test_method_called_b)
        self.assertTrue(core.get_by_name('module_c').test_method_called_c)

    @unittest.mock.patch("importlib.import_module")
    def test_call_success_priority(self, import_module):
        class TestInterface(abc.ABC):
            @abc.abstractmethod
            def test_method(self):
                ...

        class TestModuleB:
            __name__ = "module_b"

            class Plugin(openpaperwork_core.PluginBase, TestInterface):
                PRIORITY = 33

                def __init__(self, core):
                    super().__init__(core)
                    self.test_method_called_b = False

                def test_method(self):
                    self.test_method_called_b = True
                    return None

        class TestModuleC:
            __name__ = "module_c"

            class Plugin(openpaperwork_core.PluginBase, TestInterface):
                PRIORITY = 22

                def __init__(self, core):
                    super().__init__(core)
                    self.test_method_called_c = False

                def test_method(self):
                    self.test_method_called_c = True
                    return "value"

        class TestModuleD(object):
            __name__ = "module_d"

            class Plugin(openpaperwork_core.PluginBase, TestInterface):
                PRIORITY = 11

                def __init__(self, core):
                    super().__init__(core)
                    self.test_method_called_d = False

                def test_method(self):
                    self.test_method_called_d = True
                    return None

        core = openpaperwork_core.Core(auto_load_dependencies=True)

        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        import_module.return_value = TestModuleC()
        core.load('module_c')
        import_module.assert_called_once_with('module_c')

        import_module.reset_mock()
        import_module.return_value = TestModuleD()
        core.load('module_d')
        import_module.assert_called_once_with('module_d')

        import_module.reset_mock()
        # interface already satisfied --> won't load 'module_a'
        core.init()

        r = core.call_success(TestInterface.test_method)
        self.assertEqual(r, "value")
        self.assertTrue(core.get_by_name('module_b').test_method_called_b)
        self.assertTrue(core.get_by_name('module_c').test_method_called_c)
        self.assertFalse(core.get_by_name('module_d').test_method_called_d)

    @unittest.mock.patch("importlib.import_module")
    def test_priority(self, import_module):
        class TestInterface(abc.ABC):
            @abc.abstractmethod
            def test_method(self):
                ...

        class TestModuleA:
            __name__ = "module_a"

            class Plugin(openpaperwork_core.PluginBase, TestInterface):
                PRIORITY = 22

                def test_method(self):
                    return "A"

        class TestModuleB:
            __name__ = "module_b"

            class Plugin(openpaperwork_core.PluginBase, TestInterface):
                PRIORITY = 33

                def test_method(self):
                    return "B"

        core = openpaperwork_core.Core(auto_load_dependencies=True)

        import_module.return_value = TestModuleA()
        core.load('module_a')
        import_module.assert_called_once_with('module_a')

        import_module.reset_mock()
        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        core.init()

        r = core.call_success(TestInterface.test_method)
        self.assertEqual(r, "B")


class TestDependencies(unittest.TestCase):
    @unittest.mock.patch("importlib.import_module")
    def test_default_interface(self, import_module):
        class TestInterface(abc.ABC):
            @abc.abstractmethod
            def test_method(self):
                ...

        class SomeInterface(abc.ABC):
            pass

        class TestModuleA:
            __name__ = "module_a"

            class Plugin(openpaperwork_core.PluginBase, TestInterface, SomeInterface):
                def __init__(self, core):
                    super().__init__(core)
                    self.test_method_called = False
                    self.init_called = True

                def test_method(self):
                    self.test_method_called = True

        class TestModuleB:
            __name__ = "module_b"

            class Plugin(openpaperwork_core.PluginBase, SomeInterface):
                def __init__(self, core):
                    super().__init__(core)
                    self.init_called = True

                @classmethod
                def get_deps(cls):
                    return [
                        openpaperwork_core.Dependency(
                            interface=TestInterface,
                            defaults=['module_a'],
                        ),
                    ]

        core = openpaperwork_core.Core(auto_load_dependencies=True)

        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        import_module.return_value = TestModuleA()
        core.init()  # will load 'module_a' because of dependencies
        import_module.assert_called_once_with('module_a')
        self.assertTrue(core.get_by_name('module_a').init_called)
        self.assertTrue(core.get_by_name('module_b').init_called)

        core.call_all(TestInterface.test_method)
        self.assertTrue(core.get_by_name('module_a').test_method_called)

    @unittest.mock.patch("importlib.import_module")
    def test_dependency_error(self, import_module):
        self.init_called = False

        class TestInterface(abc.ABC):
            pass

        class SomeInterface(abc.ABC):
            pass

        class TestModuleA:
            __name__ = "module_a"

            class Plugin(openpaperwork_core.PluginBase, TestInterface, SomeInterface):
                def __init__(s, core):
                    super().__init__(core)
                    self.init_called = True

        class TestModuleB:
            __name__ = "module_b"

            class Plugin(openpaperwork_core.PluginBase, SomeInterface):
                @classmethod
                def get_deps(cls):
                    return [
                        openpaperwork_core.Dependency(
                            interface=TestInterface,
                            defaults=['module_a'],
                        )
                    ]

                def __init__(s, core):
                    super().__init__(core)
                    self.init_called = True

        core = openpaperwork_core.Core(auto_load_dependencies=False)

        import_module.return_value = TestModuleB()
        core.load('module_b')
        import_module.assert_called_once_with('module_b')

        import_module.reset_mock()
        import_module.return_value = TestModuleA()
        self.assertRaises(openpaperwork_core.DependencyException, core.init)
