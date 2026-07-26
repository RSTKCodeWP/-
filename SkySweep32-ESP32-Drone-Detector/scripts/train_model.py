import os
import sys
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout

def generate_synthetic_data(num_samples=1000):
    # ML_INPUT_SIZE = 37 (32 RSSI values + 5 protocol flags)
    # 5 Output classes: Unknown (0), Phantom (1), Mavic (2), FPV (3), Military (4)
    X = np.zeros((num_samples, 37), dtype=np.float32)
    y = np.zeros((num_samples,), dtype=np.int32)
    
    for i in range(num_samples):
        class_id = np.random.randint(0, 5)
        y[i] = class_id
        
        # Base noise
        X[i, :32] = np.random.normal(0.5, 0.1, 32)
        
        if class_id == 1: # Phantom (OcuSync/WiFi, 2.4/5.8Ghz)
            X[i, 35] = 1.0 # 2400Active
            X[i, 36] = 1.0 # 5800Active
            X[i, :32] += np.random.normal(0.2, 0.05, 32) # High RSSI variance
        elif class_id == 2: # Mavic (OcuSync, smoother)
            X[i, 35] = 1.0
            X[i, :32] += np.random.normal(0.1, 0.02, 32)
        elif class_id == 3: # FPV (CRSF, Analog Video, 900MHz, 5.8GHz)
            X[i, 33] = 1.0 # CRSF flag
            X[i, 34] = 1.0 # 900MHz
            X[i, 36] = 1.0 # 5.8GHz
            X[i, :32] += np.random.normal(0.3, 0.15, 32) # Very spiky RSSI
        elif class_id == 4: # Military (MAVLink, 900MHz)
            X[i, 32] = 1.0 # MAVLink
            X[i, 34] = 1.0 # 900MHz
            
        # Ensure values are within [0, 1] range
        X[i] = np.clip(X[i], 0.0, 1.0)
        
    return X, y

def main():
    print("Generating synthetic drone RF dataset...")
    X, y = generate_synthetic_data(5000)
    
    # Define model
    model = Sequential([
        Dense(16, activation='relu', input_shape=(37,)),
        Dropout(0.2),
        Dense(8, activation='relu'),
        Dense(5, activation='softmax')
    ])
    
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    
    print("Training model...")
    model.fit(X, y, epochs=15, batch_size=32, validation_split=0.2, verbose=1)
    
    # Convert to TFLite
    print("Converting to TFLite...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_model = converter.convert()
    
    # Generate C array
    print("Generating C array for model_data.h...")
    hex_array = ', '.join([f'0x{byte:02x}' for byte in tflite_model])
    
    header_content = f"""#ifndef MODEL_DATA_H
#define MODEL_DATA_H

#ifdef MODULE_ML

// Auto-generated TensorFlow Lite Micro model for SkySweep32
// Trained on synthetic RF signature data.

const unsigned char model_data[] = {{
    {hex_array}
}};

const unsigned int model_data_len = {len(tflite_model)};

#endif // MODULE_ML
#endif // MODEL_DATA_H
"""
    
    with open('src/model_data.h', 'w') as f:
        f.write(header_content)
        
    print(f"Successfully wrote {len(tflite_model)} bytes to src/model_data.h")

if __name__ == '__main__':
    main()
