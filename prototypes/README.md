# WeKnora Bridge Prototype

Disposable logic prototype for the deployment decision. Run with:

```powershell
python prototypes/weknora_bridge.py
```

The intended path is `start-ubuntu -> import-sample -> run-poc -> pass-poc -> adopt-backend`.
Before `pass-poc`, the active backend remains `RAG-Tech`; `rollback` always returns to it.
