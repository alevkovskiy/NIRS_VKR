TEMPLATE = app
TARGET = transport-tests
CONFIG += console testcase c++11
QT += core network gui testlib
SOURCES += transport_test.cpp ../src/apiclient.cpp
HEADERS += ../src/apiclient.h
