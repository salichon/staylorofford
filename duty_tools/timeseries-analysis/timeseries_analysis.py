# -*- coding: utf-8 -*-
"""
Query timeseries data from FDSN and perform analysis and plotting on it.
"""
import datetime
import obspy
from obspy.clients.fdsn import Client
import matplotlib.pyplot as plt
import numpy as np


def query_fdsn(station, location, channel, starttime, endtime):
    """
    Query FDSN for timeseries data. Input parameter can be specific or include ? wildcard
    :param: station: site code to get data from (string)
    :param: location: location code to get data from (string)
    :param: channel: channel code to get data from (string)
    :param: starttime: UTC start time of desired data (ISO8601 string)
    :param: endtime: UTC end time of desired data (ISO8601 string)
    :return: obspy stream object containing requested data
    """
    client = Client("https://service-nrt.geonet.org.nz")
    stream = client.get_waveforms(network='NZ',
                                  station=station,
                                  channel=channel,
                                  location=location,
                                  starttime=starttime,
                                  endtime=endtime)
    return stream


# Set parameters for which data to analyse using lists of strings
stations = ['RLNS']
locations = ['??']
channels = ['HNZ']
starttime = '2020-06-24T22:20:01Z'
endtime = '2020-06-24T22:21:01Z'
window_length = 61  # Window length to plot in seconds

# Set how to filter the data, if at all. Use filter_type=None to negate filtering. Filter types are those in obspy.
filter_type = 'bandpass'
minimum_frequency = 2
maximum_frequency = 15

# Set whether to plot spectrograms instead of seismograms. Use None to negative spectrogram plotting.
# Note: if both spectrogram and normalise are true, then time domain waveforms will be plotted over spectrograms.
spectrogram = False

# Set whether to normalise each trace. Use None or False to negate normalisation.
# Note: if both spectrogram and normalise are true, then time domain waveforms will be plotted over spectrograms.
normalise = False

# Reference times to overlay on plots. Use None to negate reference time plotting. Time format is ISO8601.
reference_times = None

if reference_times:
    for n in range(len(reference_times)):
        reference_times[n] = datetime.datetime.strptime(reference_times[n],
                                                        '%Y-%m-%dT%H:%M:%SZ')

# Prepare loop for iterative plotting
current_time_dt = datetime.datetime.strptime(starttime,
                                             '%Y-%m-%dT%H:%M:%SZ')
end_time_dt = datetime.datetime.strptime(endtime,
                                         '%Y-%m-%dT%H:%M:%SZ')
while current_time_dt <= end_time_dt:

    # Set windowing
    window_start = current_time_dt
    window_end = (current_time_dt + datetime.timedelta(seconds=window_length))

    # Define minor axis
    minor_axis_ticks = []
    axis_point = current_time_dt
    while axis_point <= (current_time_dt + datetime.timedelta(seconds=10)):
        minor_axis_ticks.append(axis_point)
        axis_point += datetime.timedelta(seconds=10)

    # Query the data from FDSN
    stream = obspy.core.stream.Stream()
    for station in stations:
        for location in locations:
            for channel in channels:
                query_stream = query_fdsn(station,
                                          location,
                                          channel,
                                          obspy.UTCDateTime(window_start),
                                          obspy.UTCDateTime(window_end))
            stream += query_stream

    # Filter the data as desired
    if filter_type:
        stream = stream.detrend(type='simple')
        stream = stream.filter(type=filter_type,
                               freqmin=minimum_frequency,
                               freqmax=maximum_frequency)

    # Find min/max values of each trace
    min_max_values = [[0] * len(stream),
                      [0] * len(stream),
                      [0] * len(stream),
                      [0] * len(stream),
                      [''] * len(stream)]
    for n in range(len(stream)):
        if normalise and not spectrogram:
            stream[n].data = stream[n].data / max(abs(min(stream[n].data)),
                                                  max(stream[n].data))
        if normalise and spectrogram:

            # First shift the data so the mean sits at the middle of the nyquist frequency range
            mean_value = np.mean(stream[n].data)
            shift_value = mean_value - 25
            stream[n].data = stream[n].data - shift_value

            # Then find the max-min range in the normalised data and scale the data to the nyquist frequency range
            max_min_range = max(stream[n].data) - min(stream[n].data)
            scaling_factor = 50 / max_min_range
            stream[n].data = stream[n].data * scaling_factor

            # Then find how much the data needs to be shifted by to sit at the centre of the nyquist frequency range
            shift_value = max(50 - max(stream[n].data), 0 - min(stream[n].data))
            stream[n].data = stream[n].data + shift_value
        min_max_values[0][n] = stream[n].stats.starttime
        min_max_values[1][n] = stream[n].stats.endtime
        min_max_values[2][n] = min(stream[n].data)
        min_max_values[3][n] = max(stream[n].data)
        min_max_values[4][n] = 'NZ.' + stream[n].stats.station + '.' + stream[n].stats.location + '.' + \
                               stream[n].stats.channel
    min_plot_time = min(min_max_values[0])
    max_plot_time = max(min_max_values[1])

    # Pad out traces to align all on minimum time
    stream.trim(starttime=min_plot_time,
                endtime=max_plot_time,
                pad=True,
                fill_value=None)

    # Update reference times to be relative to minimum data start time
    if reference_times:
        for m in range(len(reference_times)):
            reference_times[m] = (reference_times[m] - min_plot_time.datetime).total_seconds()

    # Plot the data and overlay reference times if desired
    fig = plt.figure(figsize=(12,9))
    stream.plot(fig=fig)#,
                # type='relative',
                # zorder=2)
    for n in range(len(fig.axes)):
        axis = fig.axes[n]
        plotting_stream = axis.texts[0]._text
        if not spectrogram:
            min_max_index = min_max_values[4].index(plotting_stream)
            axis.set_ylim(min_max_values[2][min_max_index],
                          min_max_values[3][min_max_index])
            axis.locator_params(axis='y',
                                nbins=3)
            axis.grid(axis='x',
                      which='both')
            if reference_times:
                axis.vlines(x=reference_times,
                            ymin=min_max_values[2][min_max_index],
                            ymax=min_max_values[3][min_max_index],
                            linestyles='dashed',
                            colors='red')
        else:
            stream[n].spectrogram(axes=axis,
                                  zorder=1)
            axis.set_ylim(0, 50)
            axis.locator_params(axis='y',
                                nbins=3)
            if reference_times:
                axis.vlines(x=reference_times,
                            ymin=0,
                            ymax=50,
                            linestyles='dashed',
                            colors='red')
    plt.gcf().autofmt_xdate()
    plt.show()
    plt.savefig(str(window_start) + '_' + str(window_end) + '.png',
                format='png',
                dpi=300)

    # Increase plotting window start time
    current_time_dt += datetime.timedelta(seconds=window_length)
