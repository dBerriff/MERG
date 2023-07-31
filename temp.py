from machine import Pin, PWM
help(Pin)
help(PWM)
pwm0 = PWM(Pin(0))
pwm0.freq(50)
print(pwm0, pwm0.freq())