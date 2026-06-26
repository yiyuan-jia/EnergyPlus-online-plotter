from eplus_plotter.ring_buffer import RingBuffer


def test_appends_in_order():
    b = RingBuffer(5)
    for i in range(3):
        b.append(float(i), float(i * 10))
    x, y = b.xy()
    assert list(x) == [0.0, 1.0, 2.0]
    assert list(y) == [0.0, 10.0, 20.0]
    assert len(b) == 3


def test_overwrites_oldest_when_full():
    b = RingBuffer(3)
    for i in range(5):  # 0,1,2,3,4 -> keep the last 3
        b.append(float(i), float(i * 10))
    x, y = b.xy()
    assert list(x) == [2.0, 3.0, 4.0]
    assert list(y) == [20.0, 30.0, 40.0]
    assert len(b) == 3


def test_empty():
    b = RingBuffer(4)
    x, y = b.xy()
    assert len(b) == 0
    assert list(x) == []
    assert list(y) == []
