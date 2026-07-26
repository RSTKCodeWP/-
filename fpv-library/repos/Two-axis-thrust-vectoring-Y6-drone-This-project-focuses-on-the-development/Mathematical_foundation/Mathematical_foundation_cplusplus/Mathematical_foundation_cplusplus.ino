#include <math.h>

double rx1 = 0;
double ry1 = -0.02;
double rz1 = 0;
double rx2 = -0.01;
double ry2 = 0.015;
double rz2 = 0;
double rx3 = 0.01;
double ry3 = 0.015;
double rz3 = 0;
double b [6] [1] = {
  {0},
  {0},
  {0},
  {0},
  {0},
  {1},
};
double L [6] [6] = {0};
double A [6] [9] = {
  {1, 0, 0, 1, 0, 0, 1, 0, 0},
  {0, 1, 0, 0, 1, 0, 0, 1, 0},
  {0, 0, 1, 0, 0 ,1, 0, 0, 1},
  {0, -rz1, ry1, 0, -rz2, ry2, 0, -rz3, ry3},
  {rz1, 0, -rx1, rz2, 0, -rx2, rz3, 0, -rx3},
  {-ry1, rx1, 0, -ry2, rx2, 0, -ry3, rx3, 0},
};

void setup(){

  Serial.begin(9600);
  if(!Serial){
    while(1);
  }

  //***// MATRIX P CALCULATION (A·A^T) //***//

  double sumatorio;
  double P [6] [6];
  for(int i = 0; i < 6; i++){
    for(int k = 0; k < 6; k++){
      sumatorio = 0;
      for(int j = 0; j < 9; j++){
        sumatorio = sumatorio + A [i] [j] * A [k] [j];
      }
      P [i] [k] = sumatorio;
    }
  }

  //***// MATRIX L CALCULATION (Cholesky)//***//

  double sumatorio1;
  double sumatorio2;

  L [0] [0] = sqrt(P [0] [0]);
  for(int i = 1; i < 6; i++){
    for(int j = 0; j < i; j++){
      sumatorio1 = 0;
      for(int k = 0; k < j; k++){
        sumatorio1 = sumatorio1 + (L [i] [k] * L [j] [k]);
      }
      L [i] [j] = (1.0/L [j] [j]) * (P [i] [j] - sumatorio1); 
    }
    sumatorio2 = 0;
    for(int k = 0; k < i; k++){
      sumatorio2 = sumatorio2 + (L [i] [k] * L [i] [k]);
    }
    double raiznoneg = (P [i] [i] - sumatorio2);
    if(raiznoneg < 0) raiznoneg = 0;
    L [i] [i] = sqrt(raiznoneg);
  }
}

void loop() {
  double max_value [9] [1] = {0};
  double act_value [9] [1] = {0};
    
  //***// L·y = b SOLVING //***//

  double y [6] [1] = {0};
  double sumatorio3;

  for(int i = 0; i < 6; i++){
    sumatorio3 = 0;
    for(int j = 0; j < i; j++){
      sumatorio3 = sumatorio3 + L [i] [j] * y [j] [0];
    }
    y [i] [0] = (b [i] [0] - sumatorio3)/L [i] [i];
  }

  //***// L^T·u = y SOLVING //***//

  double u [6] [1] = {0};
  double sumatorio4;

  for(int i = 5; i >= 0; i--){
    sumatorio4 = 0;
    for(int j = i + 1; j < 6; j++){
      sumatorio4 = sumatorio4 + L [j] [i] * u [j] [0];
    }
    u [i] [0] = (y [i] [0] - sumatorio4)/L [i] [i];
  }

  //***// MATRIX x CALCULATION (A^T·u) //***//

  double sumatorio5;
  double x [9] [1] = {0};

  for(int i = 0; i < 9; i++){
    sumatorio5 = 0;
    for(int j = 0; j < 6; j++){
      sumatorio5 = sumatorio5 + (A [j] [i] * u [j] [0]);
    }
    x [i] [0] = sumatorio5;
  }

  //***// PRINTING OF x ON THE SERIAL MONITOR //***//

  Serial.println("Matrix x (result):");
  for(int i = 0; i < 9; i++){
    Serial.println(x [i] [0], 6);
  }

  //***// Ft_i CALCULATION //***//

  double Ft_i [3] [1] = {0};

  for(int j = 0; j < 3; j++){
    int i = j * 3;
    Ft_i [j] [0] = sqrt(x [i] [0] * x [i] [0] + x [i+1] [0] * x [i+1] [0] + x [i+2] [0] * x [i+2] [0]);
  }

  //***// servo_x & servo_y CALCULATION //***//

  double angulosgimbal [6] [1] = {
  {atan2(x [1] [0], sqrt(x [0] [0] * x [0] [0] + x [2] [0] * x [2] [0]))},
  {atan2(-x [0] [0], x [2] [0])},
  {atan2(x [4] [0], sqrt(x [3] [0] * x [3] [0] + x [5] [0] * x [5] [0]))},
  {atan2(-x [3] [0], x [5] [0])},
  {atan2(x [7] [0], sqrt(x [6] [0] * x [6] [0] + x [8] [0] * x [8] [0]))},
  {atan2(-x [6] [0], x [8] [0])},
  };

  //***// PRINTING OF angulosgimbal ON THE SERIAL MONITOR //***//

  Serial.println("Matrix angulosgimbal:");

  for(int i = 0; i < 6; i++){
    Serial.println(angulosgimbal [i] [0]);
  }

  //***// OBTENTION OF THE PSEUDOINVERSE MATRIX  A^+ (Ap) //***//

  double e_i [6] [1] = {0};
  double y_i [6] [1] = {0};
  double u_i [6] [1] = {0};
  double Ap [9] [6] = {0};

  for(int i = 0; i < 6; i++){
    for(int j = 0; j < 6; j++){
    y_i [j][0]=0.0;
    u_i [j][0]=0.0;
    }
    for(int j = 0; j < 6; j++) e_i [j] [0] = 0.0;
    e_i [i] [0] = 1.0;
    for(int m = 0; m < 6; m++){ //***// L·y_i = e_i SOLVING //***//
      sumatorio3 = 0;
      for(int n = 0; n < m; n++){
        sumatorio3 = sumatorio3 + L [m] [n] * y_i [n] [0];
      }
      y_i [m] [0] = (e_i [m] [0] - sumatorio3)/L [m] [m];
    }
    for(int m = 5; m >= 0; m--){ //***// L^T·u_i = y_i SOLVING //***//
      sumatorio4 = 0;
      for(int n = m + 1; n < 6; n++){
        sumatorio4 = sumatorio4 + L [n] [m] * u_i [n] [0];
      }
      u_i [m] [0] = (y_i [m] [0] - sumatorio4)/L [m] [m];
    }
    for(int m = 0; m < 9; m++){ //***// MATRIX x_i (A^T·u_i) CALCULATION //***//
      sumatorio5 = 0;
      for(int n = 0; n < 6; n++){
        sumatorio5 = sumatorio5 + (A [n] [m] * u_i [n] [0]);
      }
      Ap [m] [i] = sumatorio5;
    }
  }
  
  //***// PRINTING OF A^+ (Ap) ON THE SERIAL MONITOR //***//

  Serial.println("Matrix Ap:");
  for(int i = 0; i < 9; i++){
    for(int j = 0; j < 6; j++){
      if(j < 5) Serial.print(Ap [i] [j]) && Serial.print(", ");
      if(j == 5) Serial.println(Ap [i] [j]);
    }
  }

  //***// A·A^+ = I_6 VERIFICATION //***//

  double sumatorio6;
  double AAp [6] [6] = {0};

  for(int i = 0; i < 6; i++){
    for(int j = 0; j < 6; j++){
      sumatorio6 = 0.0;
      for(int k = 0; k < 9; k++){
        sumatorio6 = sumatorio6 + (A [i] [k] * Ap [k] [j]);
      }
      AAp [i] [j] = sumatorio6;
    }
  }

  //***// PRINTING OF AAp ON THE SERIAL MONITOR //***//

  Serial.println("Matrix AAp (it must be almost I_6):");
  for(int i = 0; i < 6; i++){
    for(int j = 0; j < 6; j++){
      if(j < 5) Serial.print(AAp [i] [j]) && Serial.print(", ");
      if(j == 5) Serial.println(AAp [i] [j]);
    }
  }
  while(1);
}