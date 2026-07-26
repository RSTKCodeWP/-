file(GLOB GUI_SRC_LIST
        *.cpp
        *.c
        *.h
)

target_sources(${PROJECT_NAME} PRIVATE ${GUI_SRC_LIST})
