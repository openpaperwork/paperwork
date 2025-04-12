import abc


class AutoscrollingGesture(abc.ABC):
    @abc.abstractmethod
    def gesture_enable_autoscrolling(self, scrollview):
        ...
