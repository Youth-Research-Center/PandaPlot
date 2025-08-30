### Basic Widget

```python 
class BasicWidget(EventBusComponentMixin, QWidget):
    def __init__(self, app_context: AppContext, parent: QWidget):
        super().__init__(event_bus=app_context.event_bus, parent=parent)
        self._logger = logging.getLogger(__name__)

        self._setup_ui()
        self._apply_theme()
        self._setup_event_subscriptions()

    def _setup_ui(self):
        pass

    def _setup_event_subscriptions(self):
        pass

    def _apply_theme(self):
        pass
```

### Basic Command
