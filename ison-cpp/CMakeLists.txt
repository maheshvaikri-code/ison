cmake_minimum_required(VERSION 3.14)
project(ison_cpp
    VERSION 1.0.0
    DESCRIPTION "ISON v1.0 Parser - Interchange Simple Object Notation for C++"
    HOMEPAGE_URL "https://www.ison.dev"
    LANGUAGES CXX
)

# C++11 minimum (C++17 optional for std::optional)
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Options
option(ISON_BUILD_TESTS "Build tests" ON)
option(ISON_BUILD_EXAMPLES "Build examples" ON)
option(ISON_INSTALL "Install headers" ON)

# Header-only library
add_library(ison_cpp INTERFACE)
add_library(ison::cpp ALIAS ison_cpp)

target_include_directories(ison_cpp
    INTERFACE
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_compile_features(ison_cpp INTERFACE cxx_std_11)

# Tests
if(ISON_BUILD_TESTS)
    enable_testing()
    add_executable(test_ison_cpp tests/test_ison_parser.cpp)
    target_link_libraries(test_ison_cpp PRIVATE ison_cpp)

    # Add compiler warnings
    if(MSVC)
        target_compile_options(test_ison_cpp PRIVATE /W4)
    else()
        target_compile_options(test_ison_cpp PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME ison_cpp_tests COMMAND test_ison_cpp)
endif()

# Examples
if(ISON_BUILD_EXAMPLES)
    add_executable(ison_example examples/example.cpp)
    target_link_libraries(ison_example PRIVATE ison_cpp)
endif()

# Installation
if(ISON_INSTALL)
    include(GNUInstallDirs)

    install(TARGETS ison_cpp
        EXPORT ison_cppTargets
        INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    )

    install(FILES include/ison_parser.hpp
        DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    )

    install(EXPORT ison_cppTargets
        FILE ison_cppTargets.cmake
        NAMESPACE ison::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/ison_cpp
    )

    # Package config
    include(CMakePackageConfigHelpers)

    configure_package_config_file(
        ${CMAKE_CURRENT_SOURCE_DIR}/cmake/ison_cppConfig.cmake.in
        ${CMAKE_CURRENT_BINARY_DIR}/ison_cppConfig.cmake
        INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/ison_cpp
    )

    write_basic_package_version_file(
        ${CMAKE_CURRENT_BINARY_DIR}/ison_cppConfigVersion.cmake
        VERSION ${PROJECT_VERSION}
        COMPATIBILITY SameMajorVersion
    )

    install(FILES
        ${CMAKE_CURRENT_BINARY_DIR}/ison_cppConfig.cmake
        ${CMAKE_CURRENT_BINARY_DIR}/ison_cppConfigVersion.cmake
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/ison_cpp
    )
endif()
