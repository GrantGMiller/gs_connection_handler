class C:

    def __init__(self):
        self._disconnected = None

    @property
    def Disconnected(self):
        return self._disconnected

    @Disconnected.setter
    def Disconnected(self, func):
        self._disconnected = func


c = C()

print(c.__setattr__)


def NewSetAttr(self, *args, **kwargs):
    print('NewSetAttr(a={}, k={})'.format(args, kwargs))


oldSetAttr = c.__setattr__
c.__setattr__ = NewSetAttr

c.Disconnected = 'test'
c.test = 'test'
