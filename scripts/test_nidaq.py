
from lab_instruments.nidaq import *

# Generate a train of pulses
npulses = 4
delay = 1.  # s
interval = 3.  # s
train = trigger_train(delay, interval, npulses)