################################################################################
#
# fpv-streamer
#
################################################################################

FPV_STREAMER_VERSION = 1.0.0
FPV_STREAMER_SITE = $(call github,fpv-streamer,project,$(FPV_STREAMER_VERSION))
FPV_STREAMER_SOURCE = fpv-streamer-$(FPV_STREAMER_VERSION).tar.gz
FPV_STREAMER_DEPENDENCIES = ffmpeg json-c
FPV_STREAMER_LICENSE = MIT
FPV_STREAMER_LICENSE_FILES = LICENSE
FPV_STREAMER_CONFIG_SCRIPTS = fpv-streamer-config

# Enable debug mode if selected
FPV_STREAMER_CONF_OPTS += $(if $(BR2_PACKAGE_FPV_STREAMER_DEBUG),--enable-debug,)
FPV_STREAMER_CONF_OPTS += $(if $(BR2_PACKAGE_FPV_STREAMER_HARDWARE_ENCODER),--enable-hw-encoder,)
FPV_STREAMER_CONF_OPTS += $(if $(BR2_PACKAGE_FPV_STREAMER_OBJECT_DETECTION),--enable-object-detection,)
FPV_STREAMER_CONF_OPTS += $(if $(BR2_PACKAGE_FPV_STREAMER_WEB_INTERFACE),--enable-web-interface,)

# Cross-compilation settings
FPV_STREAMER_MAKE = $(MAKE1)

define FPV_STREAMER_CONFIGURE_CMDS
    (cd $(@D); \
    mkdir -p build; \
    cd build; \
    cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_TOOLCHAIN_FILE=../cmake/arm-toolchain.cmake \
        -DCMAKE_INSTALL_PREFIX=/usr \
        $(FPV_STREAMER_CONF_OPTS))
endef

define FPV_STREAMER_BUILD_CMDS
    (cd $(@D)/build && \
    $(FPV_STREAMER_MAKE) -j$$(BR2_JLEVEL))
endef

define FPV_STREAMER_INSTALL_TARGET_CMDS
    (cd $(@D)/build && \
    $(FPV_STREAMER_MAKE) DESTDIR=$(TARGET_DIR) install)
endef

define FPV_STREAMER_INSTALL_INIT
    $(INSTALL) -m 0755 -D $(@D)/build/fpv-streamer $(TARGET_DIR)/usr/bin/fpv-streamer
endef

define FPV_STREAMER_UNINSTALL
    rm -f $(TARGET_DIR)/usr/bin/fpv-streamer
endef

$(eval $(generic-package))