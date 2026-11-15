TEMPLATE = app
TARGET = live-api-tests
CONFIG += console testcase c++11
QT += core network gui testlib
SOURCES += live_api_test.cpp ../src/apiclient.cpp
HEADERS += ../src/apiclient.h
