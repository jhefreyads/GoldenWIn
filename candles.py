import candles_crypto
import candles_iq
import asyncio

async def iq():
    await asyncio.to_thread(candles_iq.main)

async def crypto():
    await asyncio.to_thread(candles_crypto.main)

async def main():
    await asyncio.gather(iq())

if __name__ == "__main__":
    asyncio.run(main())
