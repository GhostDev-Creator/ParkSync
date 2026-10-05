import cv2
import numpy as np
import base64
import face_recognition
import os
from dotenv import load_dotenv
from database.setup_db import SessionLocal
from database.models import MoradorModel

load_dotenv()
camera_facial_entrada = os.getenv('PE_FACE_CAM')
tolerancia = os.getenv('FACIAL_THRESHOLD')


def extract_embedding(foto_frontCadastro: str):
    try:
        encoded_img = foto_frontCadastro.split(",")[1] if "," in foto_frontCadastro else foto_frontCadastro

        img_buffer = np.frombuffer(base64.b64decode(encoded_img), np.uint8)
        img = cv2.imdecode(img_buffer, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        encodings = face_recognition.face_encodings(rgb_img)

        if len(encodings) > 0:
            return encodings[0].tolist()
        else:
            return None
    except Exception as e:
        print(f"Erro no módulo de reconhecimento facial: {e}")
        return None


def verify_embedding():
    db = SessionLocal()

    try:
        moradores = db.query(MoradorModel).filter(MoradorModel.face_encoding.isnot(None)).all()

        encodings_conhecidos = []
        nomes_conhecidos = []

        for m in moradores:
            encodings_conhecidos.append(np.array(m.face_encoding))
            nomes_conhecidos.append(f"ID {m.id} - {m.nome}")

        print(f"{len(moradores)} moradores carregados na memória!")

        video_capture = cv2.VideoCapture(camera_facial_entrada)
        video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        cv2.namedWindow("Verificacao Facial - ParkSync", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Verificacao Facial - ParkSync", 1920, 1080)

        while True:
            ret, frame = video_capture.read()
            if not ret:
                break

            frame = cv2.resize(frame, (1920, 1080))

            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            for (top, right, bottom, left), face_encodings in zip(face_locations, face_encodings):
                nome_exibicao = "Desconhecido"
                cor_caixa = (0, 0, 255)

                if encodings_conhecidos:
                    matches = face_recognition.compare_faces(encodings_conhecidos, face_encodings, tolerance=tolerancia)
                    face_distances = face_recognition.face_distance(encodings_conhecidos, face_encodings)

                    if len(face_distances) > 0:
                        best_match_index = np.argmin(face_distances)
                        if matches[best_match_index]:
                            nome_exibicao = nomes_conhecidos[best_match_index]
                            cor_caixa = (0, 255, 0)

                top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4

            cv2.rectangle(frame, (left, top), (right, bottom), cor_caixa, 2)
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), cor_caixa, cv2.FILLED)
            cv2.putText(frame, nome_exibicao, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow("Verificacao Facial - ParkSync", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        db.close()
        video_capture.release()
        cv2.destroyAllWindows()