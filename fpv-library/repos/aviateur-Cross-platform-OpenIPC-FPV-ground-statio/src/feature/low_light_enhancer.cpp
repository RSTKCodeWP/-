#include "low_light_enhancer.h"

#include <fstream>
#include <opencv2/dnn.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>

// See https://github.com/hpc203/low-light-image-enhancement-opencv-dnn

LowLightEnhancer::LowLightEnhancer(const std::string& model_path, float exposure) {
    net_ = cv::dnn::readNet(model_path);

    size_t pos = model_path.rfind("_");
    size_t pos_ = model_path.rfind(".");
    int len = pos_ - pos - 1;
    std::string hxw = model_path.substr(pos + 1, len);

    pos = hxw.rfind("x");
    std::string h = hxw.substr(0, pos);
    len = hxw.length() - pos;
    std::string w = hxw.substr(pos + 1, len);
    input_height_ = std::stoi(h);
    input_width_ = std::stoi(w);
    cv::Mat one = cv::Mat_<float>(1, 1) << exposure;
    exposure_ = cv::dnn::blobFromImage(one);
}

cv::Mat LowLightEnhancer::detect(const cv::Mat& grayImg) {
    auto srcImg = cv::Mat(grayImg.size(), CV_8UC3);
    cv::cvtColor(grayImg, srcImg, cv::COLOR_GRAY2BGR);

    const int srch = srcImg.rows;
    const int srcw = srcImg.cols;
    cv::Mat blob = cv::dnn::blobFromImage(srcImg,
                                          1 / 255.0,
                                          cv::Size(input_width_, input_height_),
                                          cv::Scalar(0, 0, 0),
                                          true,
                                          false);

    net_.setInput(blob, "input");
    net_.setInput(exposure_, "exposure");
    std::vector<cv::Mat> outs;
#ifdef _WIN32
    net_.enableWinograd(false); // For OpenCV 4.7
#endif
    net_.forward(outs, net_.getUnconnectedOutLayersNames());

    float* pdata = (float*)outs[0].data;
    const int out_h = outs[0].size[2];
    const int out_w = outs[0].size[3];
    const int channel_step = out_h * out_w;

    cv::Mat rmat(out_h, out_w, CV_32FC1, pdata);
    cv::Mat gmat(out_h, out_w, CV_32FC1, pdata + channel_step);
    cv::Mat bmat(out_h, out_w, CV_32FC1, pdata + 2 * channel_step);

    rmat *= 255.f;
    gmat *= 255.f;
    bmat *= 255.f;

    /// output_image = np.clip(output_image, 0, 255)
    rmat.setTo(0, rmat < 0);
    rmat.setTo(255, rmat > 255);
    gmat.setTo(0, gmat < 0);
    gmat.setTo(255, gmat > 255);
    bmat.setTo(0, bmat < 0);
    bmat.setTo(255, bmat > 255);

    std::vector<cv::Mat> channel_mats(3);
    channel_mats[0] = bmat;
    channel_mats[1] = gmat;
    channel_mats[2] = rmat;

    cv::Mat dstImg;
    merge(channel_mats, dstImg);
    dstImg.convertTo(dstImg, CV_8UC3);
    cv::resize(dstImg, dstImg, cv::Size(srcw, srch));

    auto finalImg = cv::Mat(dstImg.size(), CV_8UC1);
    cv::cvtColor(dstImg, finalImg, cv::COLOR_BGR2GRAY);

    return finalImg;
}
