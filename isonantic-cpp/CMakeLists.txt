cmake_minimum_required(VERSION 3.14)
project(isonantic
    VERSION 1.0.0
    DESCRIPTION "Type-safe validation for ISON format in C++"
    HOMEPAGE_URL "https://www.ison.dev"
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Options
option(ISONANTIC_BUILD_TESTS "Build tests" ON)
option(ISONANTIC_BUILD_EXAMPLES "Build examples" ON)
option(ISONANTIC_INSTALL "Install headers" ON)

# Header-only library
add_library(isonantic INTERFACE)
add_library(isonantic::isonantic ALIAS isonantic)

target_include_directories(isonantic
    INTERFACE
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_compile_features(isonantic INTERFACE cxx_std_17)

# Tests
if(ISONANTIC_BUILD_TESTS)
    enable_testing()
    add_executable(test_isonantic tests/test_isonantic.cpp)
    target_link_libraries(test_isonantic PRIVATE isonantic)

    if(MSVC)
        target_compile_options(test_isonantic PRIVATE /W4)
    else()
        target_compile_options(test_isonantic PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    add_test(NAME isonantic_tests COMMAND test_isonantic)
endif()

# Examples
if(ISONANTIC_BUILD_EXAMPLES)
    add_executable(isonantic_example examples/basic.cpp)
    target_link_libraries(isonantic_example PRIVATE isonantic)
endif()

# Installation
if(ISONANTIC_INSTALL)
    include(GNUInstallDirs)

    install(TARGETS isonantic
        EXPORT isonanticTargets
        INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    )

    install(FILES include/isonantic.hpp
        DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    )

    install(EXPORT isonanticTargets
        FILE isonanticTargets.cmake
        NAMESPACE isonantic::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/isonantic
    )
endif()
