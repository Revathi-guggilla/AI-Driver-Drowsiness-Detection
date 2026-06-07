import cv2
import time

def test_camera(index):
    print(f"Testing camera index {index}...")
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"Fallback: Testing camera index {index} without CAP_DSHOW...")
        cap = cv2.VideoCapture(index)
    
    if not cap.isOpened():
        print(f"Index {index} could not be opened.")
        return False
    
    ret, frame = cap.read()
    if ret:
        print(f"Successfully captured frame from index {index}.")
        # Show for 2 seconds
        # cv2.imshow(f"Camera {index}", frame)
        # cv2.waitKey(2000)
        # cv2.destroyAllWindows()
    else:
        print(f"Failed to capture frame from index {index}.")
    
    cap.release()
    return ret

if __name__ == "__main__":
    for i in range(5):
        if test_camera(i):
            print(f"Camera {i} is WORKING.")
        else:
            print(f"Camera {i} is NOT WORKING.")
