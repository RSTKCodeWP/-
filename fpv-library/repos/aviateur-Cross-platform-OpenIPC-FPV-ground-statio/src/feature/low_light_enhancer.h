#pragma once

#include <opencv2/dnn.hpp>

class LowLightEnhancer {
public:
    LowLightEnhancer(const std::string& model_path, float exposure = 0.5);
    cv::Mat detect(const cv::Mat& gray_image);

private:
    int input_width_;
    int input_height_;
    cv::Mat exposure_;
    cv::dnn::Net net_;
};
