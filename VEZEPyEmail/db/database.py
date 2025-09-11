from contextlib import asynccontextmanager


@asynccontextmanager
async def get_session():
    # Minimal stub: yield a dummy object. Replace with real AsyncSession.
    class Dummy:
        async def execute(self, *_args, **_kwargs):
            class R:
                def scalars(self):
                    class S:
                        def all(self):
                            return []

                    return S()

            return R()

    yield Dummy()
