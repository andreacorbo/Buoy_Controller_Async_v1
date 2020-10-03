for task in cfg.CRON:
    print(run, eval(task[0]), task[1], eval(task[2])))


rtc.set()
asyncio.run(ctd1.start_up(rtc))

modem1.off()
modem1.on()
asyncio.run(modem1.data_transfer(f_lock,ser_semaphore))

modem1.init_uart()
modem1.uart.write("AT+creg?\r")
while True:
    if modem1.uart.any():
        print(modem1.uart.read())
        break

asyncio.run(gps1.main(f_lock,['log'],['RMC','GSV']))

async def sc():
    i = 0
    while i < 5:
        i += 1
        print(i)
        await asyncio.sleep(1)
    print('bye')
    scheduling.set()
async def main():
    asyncio.create_task(utils.blink(3, 50, 1000, cancel_evt=scheduling))
    asyncio.create_task(utils.blink(2, 1, 2000, start_evt=scheduling))
    asyncio.create_task(sc())
    await asyncio.sleep(120)

asyncio.run(main())
