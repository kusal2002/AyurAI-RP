
"""AyurAI Live MAX30102 Monitor — research demonstration."""

from collections import deque

import numpy as np
import pandas as pd
import serial
import streamlit as st
from scipy.signal import butter, sosfiltfilt

st.set_page_config(
    page_title="AyurAI Live PPG",
    page_icon="📈",
    layout="wide",
)

st.title("AyurAI — Live Sensor Monitor")
st.caption(
    "ESP32-S3 + MAX30102 | Local USB connection | "
    "Experimental measurements only"
)

# Current firmware: 100 Hz configured, 4x FIFO averaging.
NOMINAL_RATE = 25

if "sensor_samples" not in st.session_state:
    st.session_state.sensor_samples = deque(maxlen=750)
    st.session_state.sensor_buffer = ""
    st.session_state.sensor_metrics = {}
    st.session_state.sensor_serial = None


port = st.text_input("ESP32 Serial Port", value="COM11")

left, right = st.columns(2)

with left:
    if st.button("Start Live Monitoring", use_container_width=True):
        current = st.session_state.sensor_serial

        if current is None or not current.is_open:
            try:
                connection = serial.Serial(
                    port=port,
                    baudrate=115200,
                    timeout=0,
                )

                st.session_state.sensor_serial = connection
                st.session_state.sensor_samples.clear()
                st.session_state.sensor_buffer = ""
                st.session_state.sensor_metrics = {}

                st.success("ESP32 connected!")

            except serial.SerialException as exc:
                st.error(f"Cannot connect: {exc}")

with right:
    if st.button("Stop Monitoring", use_container_width=True):
        connection = st.session_state.sensor_serial

        if connection is not None and connection.is_open:
            connection.close()

        st.session_state.sensor_serial = None
        st.info("Monitoring stopped. COM port released.")


@st.fragment(run_every="1s")
def show_live_sensor():
    connection = st.session_state.sensor_serial

    if connection is not None and connection.is_open:
        try:
            available = connection.in_waiting

            if available:
                chunk = connection.read(
                    min(available, 65536)
                ).decode("ascii", errors="replace")

                buffer = (
                    st.session_state.sensor_buffer + chunk
                )

                lines = buffer.split("\n")
                st.session_state.sensor_buffer = lines[-1][-256:]

                for raw in lines[:-1]:
                    line = raw.strip()
                    parts = line.split(",")

                    # Experimental vital-sign messages
                    if line.startswith("#METRICS,"):
                        if len(parts) == 6:
                            try:
                                st.session_state.sensor_metrics = {
                                    "hr": (
                                        None if parts[2] == "null"
                                        else int(parts[2])
                                    ),
                                    "spo2": (
                                        None if parts[3] == "null"
                                        else int(parts[3])
                                    ),
                                    "temp": (
                                        None if parts[4] == "null"
                                        else float(parts[4])
                                    ),
                                    "finger": int(parts[5]),
                                }
                            except ValueError:
                                pass
                        continue

                    # Raw RED/IR messages
                    if len(parts) == 3:
                        try:
                            timestamp, red, ir = map(int, parts)

                            if (
                                timestamp >= 0
                                and 0 <= red <= 262143
                                and 0 <= ir <= 262143
                            ):
                                st.session_state.sensor_samples.append(
                                    (timestamp, red, ir)
                                )
                        except ValueError:
                            pass

        except serial.SerialException as exc:
            st.error(f"Serial connection lost: {exc}")
            st.session_state.sensor_serial = None

    connected = (
        connection is not None and connection.is_open
    )

    if connected:
        st.success("Live sensor connected")
    else:
        st.warning("Sensor disconnected — displaying last received data")

    metrics = st.session_state.sensor_metrics
    samples = list(st.session_state.sensor_samples)

    a, b, c, d = st.columns(4)

    with a:
        hr = metrics.get("hr")
        st.metric(
            "Heart Rate (experimental)",
            f"{hr} BPM" if hr is not None else "—",
        )

    with b:
        spo2 = metrics.get("spo2")
        st.metric(
            "SpO₂ (experimental)",
            f"{spo2}%" if spo2 is not None else "—",
        )

    with c:
        st.metric(
            "Finger Contact",
            "Detected" if metrics.get("finger") == 1
            else "Not confirmed",
        )

    with d:
        st.metric("PPG Samples", len(samples))

    if len(samples) < 20:
        st.info("Waiting for RED/IR signal...")
        return

    # Approximate sample-index time axis.
    time_s = np.arange(len(samples)) / NOMINAL_RATE

    red = np.asarray(
        [sample[1] for sample in samples], dtype=float
    )
    ir = np.asarray(
        [sample[2] for sample in samples], dtype=float
    )

    st.subheader("Live Raw RED and IR Signals")

    raw_chart = pd.DataFrame(
        {
            "RED": red,
            "IR": ir,
        },
        index=time_s,
    )
    raw_chart.index.name = "Approximate seconds"

    st.line_chart(raw_chart, height=250)

    st.subheader("Filtered PPG Waveform")

    if len(samples) >= 100:
        try:
            sos = butter(
                3,
                [0.6, 3.0],
                btype="bandpass",
                fs=NOMINAL_RATE,
                output="sos",
            )

            filtered_red = sosfiltfilt(sos, red)
            filtered_ir = sosfiltfilt(sos, ir)

            # Display the most recent 10 seconds.
            window = NOMINAL_RATE * 10

            filtered_chart = pd.DataFrame(
                {
                    "Filtered RED": filtered_red[-window:],
                    "Filtered IR": filtered_ir[-window:],
                },
                index=time_s[-window:],
            )
            filtered_chart.index.name = "Approximate seconds"

            st.line_chart(filtered_chart, height=260)

        except ValueError:
            st.info("Collecting more samples for filtering.")

    st.caption(
        "Technical preview only. The 0.6–3 Hz filter does not "
        "establish signal quality, medical-grade HR/SpO₂ accuracy, "
        "haemoglobin concentration, or anaemia risk. "
        "Time uses the nominal 25 Hz FIFO rate."
    )


show_live_sensor()
